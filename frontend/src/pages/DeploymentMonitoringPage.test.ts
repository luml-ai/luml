import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { reactive } from 'vue'
import DeploymentMonitoringPage from './DeploymentMonitoringPage.vue'
import { MonitoringIneligibilityReason } from '@/lib/api/monitoring/interfaces'
import { MONITORING_SESSION_EXPIRED_MESSAGE } from '@/stores/monitoring'

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const DEPLOYMENT = 'deployment-a'
const SATELLITE_ORIGIN = 'https://sat.example.com'
const LAUNCH_URL = `${SATELLITE_ORIGIN}/monitoring/launch?token=header.payload.sig`

const store = reactive({
  status: 'loading' as string,
  reason: null as MonitoringIneligibilityReason | null,
  launchUrl: null as string | null,
  satelliteOrigin: null as string | null,
  launch: vi.fn(),
  markExpired: vi.fn(),
  reset: vi.fn(),
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: ORG, id: ORBIT, deploymentId: DEPLOYMENT } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/monitoring', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return {
    ...actual,
    useMonitoringStore: () => store,
  }
})

const iconStub = { template: '<span />' }

function mountPage() {
  return mount(DeploymentMonitoringPage, {
    global: {
      stubs: {
        Breadcrumb: { template: '<nav><slot /></nav>' },
        RouterLink: { template: '<a><slot /></a>', props: ['to'] },
        UiPageLoader: { template: '<div data-testid="loader" />' },
        Button: {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          props: ['label'],
        },
        PowerOff: iconStub,
        TriangleAlert: iconStub,
        Clock: iconStub,
        RefreshCw: iconStub,
      },
    },
  })
}

describe('DeploymentMonitoringPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.status = 'loading'
    store.reason = null
    store.launchUrl = null
    store.satelliteOrigin = null
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('launches monitoring for the routed deployment on mount', () => {
    mountPage()
    expect(store.launch).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT)
  })

  it('shows a loader while resolving', () => {
    const wrapper = mountPage()
    expect(wrapper.find('[data-testid="loader"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="monitoring-iframe"]').exists()).toBe(false)
  })

  it('shows the disabled state for monitoring off and renders no iframe', async () => {
    store.status = 'disabled'
    store.reason = MonitoringIneligibilityReason.monitoring_off
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="monitoring-disabled"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('turned off')
    expect(wrapper.find('[data-testid="monitoring-iframe"]').exists()).toBe(false)
  })

  it('shows a capability-specific message when the Satellite lacks monitoring', async () => {
    store.status = 'disabled'
    store.reason = MonitoringIneligibilityReason.capability_missing
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="monitoring-disabled"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('capability')
    expect(wrapper.find('[data-testid="monitoring-iframe"]').exists()).toBe(false)
  })

  it('shows the unavailable state with a retry that re-launches, and no iframe', async () => {
    store.status = 'unavailable'
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="monitoring-unavailable"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="monitoring-iframe"]').exists()).toBe(false)

    store.launch.mockClear()
    await wrapper.find('[data-testid="monitoring-retry"]').trigger('click')
    expect(store.launch).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT)
  })

  it('renders the full-bleed iframe with the freshly minted token when active', async () => {
    store.status = 'active'
    store.launchUrl = LAUNCH_URL
    const wrapper = mountPage()
    await flushPromises()

    const iframe = wrapper.find('[data-testid="monitoring-iframe"]')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('src')).toBe(LAUNCH_URL)
    expect(wrapper.find('[data-testid="monitoring-disabled"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="monitoring-unavailable"]').exists()).toBe(false)
  })

  it('marks the session expired on a session-expired message from the Satellite origin', async () => {
    store.status = 'active'
    store.launchUrl = LAUNCH_URL
    store.satelliteOrigin = SATELLITE_ORIGIN
    mountPage()

    window.dispatchEvent(
      new MessageEvent('message', {
        data: { type: MONITORING_SESSION_EXPIRED_MESSAGE },
        origin: SATELLITE_ORIGIN,
      }),
    )
    await flushPromises()

    expect(store.markExpired).toHaveBeenCalled()
  })

  it('ignores session-expired messages from a foreign origin', async () => {
    store.status = 'active'
    store.launchUrl = LAUNCH_URL
    store.satelliteOrigin = SATELLITE_ORIGIN
    mountPage()

    window.dispatchEvent(
      new MessageEvent('message', {
        data: { type: MONITORING_SESSION_EXPIRED_MESSAGE },
        origin: 'https://evil.example.com',
      }),
    )
    await flushPromises()

    expect(store.markExpired).not.toHaveBeenCalled()
  })

  it('offers a re-launch action in the expired state', async () => {
    store.status = 'expired'
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="monitoring-expired"]').exists()).toBe(true)
    store.launch.mockClear()
    await wrapper.find('[data-testid="monitoring-relaunch"]').trigger('click')
    expect(store.launch).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT)
  })
})
